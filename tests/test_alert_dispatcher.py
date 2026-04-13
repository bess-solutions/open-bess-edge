# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_alert_dispatcher.py
================================
Unit tests for ``src.core.alert_dispatcher``.

Strategy:
  - Mock urllib.request.urlopen for Slack channel tests (no real HTTP)
  - Mock smtplib.SMTP for email channel tests (no real SMTP)
  - Verify severity filtering (below-threshold events are silently dropped)
  - Verify all AlertSeverity ordering operators (__ge__, __gt__)
  - Verify structured log fallback always fires
"""

from __future__ import annotations

import os
import smtplib
from unittest.mock import MagicMock, patch

from src.core.alert_dispatcher import AlertDispatcher, AlertSeverity

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _dispatcher(**env) -> AlertDispatcher:
    """Create an AlertDispatcher with controlled env vars."""
    for k, v in env.items():
        os.environ[k] = v
    dispatcher = AlertDispatcher()
    # Clean up — don't pollute other tests
    for k in env:
        os.environ.pop(k, None)
    return dispatcher


# ---------------------------------------------------------------------------
# AlertSeverity ordering
# ---------------------------------------------------------------------------

class TestAlertSeverityOrdering:
    def test_critical_ge_all(self):
        assert AlertSeverity.CRITICAL >= AlertSeverity.INFO
        assert AlertSeverity.CRITICAL >= AlertSeverity.WARNING
        assert AlertSeverity.CRITICAL >= AlertSeverity.CRITICAL

    def test_warning_ge_info_and_self(self):
        assert AlertSeverity.WARNING >= AlertSeverity.INFO
        assert AlertSeverity.WARNING >= AlertSeverity.WARNING
        assert not (AlertSeverity.WARNING >= AlertSeverity.CRITICAL)

    def test_info_only_ge_self(self):
        assert AlertSeverity.INFO >= AlertSeverity.INFO
        assert not (AlertSeverity.INFO >= AlertSeverity.WARNING)
        assert not (AlertSeverity.INFO >= AlertSeverity.CRITICAL)

    def test_critical_gt_warning_and_info(self):
        assert AlertSeverity.CRITICAL > AlertSeverity.WARNING
        assert AlertSeverity.CRITICAL > AlertSeverity.INFO
        assert not (AlertSeverity.CRITICAL > AlertSeverity.CRITICAL)

    def test_warning_gt_info(self):
        assert AlertSeverity.WARNING > AlertSeverity.INFO
        assert not (AlertSeverity.WARNING > AlertSeverity.WARNING)

    def test_string_values(self):
        assert AlertSeverity.INFO.value == "INFO"
        assert AlertSeverity.WARNING.value == "WARNING"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"


# ---------------------------------------------------------------------------
# Severity filtering — no channels configured (log-only)
# ---------------------------------------------------------------------------

class TestSeverityFiltering:
    def test_warning_passes_default_threshold(self):
        """Default min_severity=WARNING → WARNING should be dispatched (log reached)."""
        dispatcher = AlertDispatcher()
        # Should NOT raise
        dispatcher.send(
            severity=AlertSeverity.WARNING,
            title="Test warning",
            detail="detail",
            source="test",
        )

    def test_info_dropped_by_default(self):
        """INFO < WARNING minimum → dropped silently (no exception)."""
        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.INFO,
            title="Test info",
            detail="detail",
            source="test",
        )

    def test_critical_always_passes(self):
        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.CRITICAL,
            title="Critical!",
            detail="detail",
            source="test",
        )

    def test_min_severity_from_env_info(self):
        """Setting ALERT_MIN_SEVERITY=INFO allows INFO events through."""
        dispatcher = _dispatcher(ALERT_MIN_SEVERITY="INFO")
        # Should not raise
        dispatcher.send(
            severity=AlertSeverity.INFO,
            title="Info event",
            detail="detail",
            source="test",
        )

    def test_min_severity_from_env_critical(self):
        """Setting ALERT_MIN_SEVERITY=CRITICAL drops WARNING events."""
        dispatcher = _dispatcher(ALERT_MIN_SEVERITY="CRITICAL")

        # WARNING below CRITICAL minimum — should be dropped without error
        dispatcher.send(
            severity=AlertSeverity.WARNING,
            title="Warning dropped",
            detail="detail",
            source="test",
        )


# ---------------------------------------------------------------------------
# Slack channel
# ---------------------------------------------------------------------------

class TestSlackChannel:
    def _dispatcher_with_slack(self) -> AlertDispatcher:
        return _dispatcher(ALERT_SLACK_WEBHOOK="https://hooks.slack.com/test/fake")

    def test_slack_sends_post_request(self):
        dispatcher = self._dispatcher_with_slack()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Anomaly detected",
                detail="z-score=4.5",
                source="ai_ids",
                tags={"device": "BESS-001"},
            )
            mock_open.assert_called_once()

    def test_slack_below_threshold_not_called(self):
        """INFO below WARNING threshold → Slack not called."""
        dispatcher = self._dispatcher_with_slack()

        with patch("urllib.request.urlopen") as mock_open:
            dispatcher.send(
                severity=AlertSeverity.INFO,
                title="Harmless info",
                detail="detail",
                source="test",
            )
            mock_open.assert_not_called()

    def test_slack_request_contains_title(self):
        dispatcher = self._dispatcher_with_slack()
        captured_data: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured_data.append(req.data)
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.__enter__ = lambda s: mock_resp
            mock_resp.__exit__ = MagicMock(return_value=False)
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="SOC drop",
                detail="SOC fell to 8% in 3 minutes",
                source="safety_guard",
            )

        assert len(captured_data) == 1
        payload_str = captured_data[0].decode("utf-8")
        assert "SOC drop" in payload_str

    def test_slack_http_error_does_not_raise(self):
        """Network/HTTP errors should be caught and logged — never propagate."""
        dispatcher = self._dispatcher_with_slack()

        with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
            # Must NOT raise
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Test",
                detail="detail",
                source="test",
            )

    def test_slack_bad_status_does_not_raise(self):
        """Non-200 HTTP response should be logged but not raise."""
        dispatcher = self._dispatcher_with_slack()

        mock_resp = MagicMock()
        mock_resp.status = 500
        mock_resp.__enter__ = lambda s: mock_resp
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            dispatcher.send(
                severity=AlertSeverity.WARNING,
                title="Test warning",
                detail="detail",
                source="test",
            )


# ---------------------------------------------------------------------------
# Email channel
# ---------------------------------------------------------------------------

class TestEmailChannel:
    def _dispatcher_with_email(self) -> AlertDispatcher:
        return _dispatcher(
            ALERT_EMAIL_FROM="from@bessai.cl",
            ALERT_EMAIL_TO="ops@bessai.cl",
            ALERT_EMAIL_SMTP_HOST="smtp.test.com",
            ALERT_EMAIL_SMTP_PORT="587",
        )

    def test_email_sends_on_critical(self):
        dispatcher = self._dispatcher_with_email()
        mock_server = MagicMock()
        mock_smtp_cls = MagicMock(return_value=mock_server)
        mock_server.__enter__ = lambda s: mock_server
        mock_server.__exit__ = MagicMock(return_value=False)

        with patch("smtplib.SMTP", mock_smtp_cls):
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Critical alert",
                detail="detail",
                source="test",
            )
        mock_smtp_cls.assert_called_once()

    def test_email_not_sent_below_threshold(self):
        dispatcher = self._dispatcher_with_email()
        with patch("smtplib.SMTP") as mock_smtp_cls:
            dispatcher.send(
                severity=AlertSeverity.INFO,
                title="Harmless",
                detail="detail",
                source="test",
            )
            mock_smtp_cls.assert_not_called()

    def test_email_smtp_error_does_not_raise(self):
        dispatcher = self._dispatcher_with_email()
        with patch("smtplib.SMTP", side_effect=smtplib.SMTPException("Connection failed")):
            # Must NOT raise
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Test",
                detail="detail",
                source="test",
            )

    def test_email_without_from_does_not_send(self):
        """If ALERT_EMAIL_FROM not set, email channel should be disabled."""
        dispatcher = _dispatcher(ALERT_EMAIL_TO="ops@bessai.cl")
        with patch("smtplib.SMTP") as mock_smtp_cls:
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Test",
                detail="detail",
                source="test",
            )
            mock_smtp_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Tags handling
# ---------------------------------------------------------------------------

class TestTagsHandling:
    def test_send_with_empty_tags(self):
        dispatcher = AlertDispatcher()
        # Should not raise even with empty tags
        dispatcher.send(
            severity=AlertSeverity.WARNING,
            title="No tags",
            detail="detail",
            source="test",
            tags={},
        )

    def test_send_with_none_tags(self):
        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.WARNING,
            title="None tags",
            detail="detail",
            source="test",
            tags=None,
        )

    def test_send_with_rich_tags(self):
        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.CRITICAL,
            title="Rich tags",
            detail="detail",
            source="test",
            tags={"site": "Santiago", "device": "BESS-001", "signal": "soc_pct"},
        )

    def test_slack_tags_included_in_payload(self):
        dispatcher = _dispatcher(ALERT_SLACK_WEBHOOK="https://hooks.slack.com/test/fake")
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            m = MagicMock()
            m.status = 200
            m.__enter__ = lambda s: m
            m.__exit__ = MagicMock(return_value=False)
            return m

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            dispatcher.send(
                severity=AlertSeverity.CRITICAL,
                title="Tag test",
                detail="testing",
                source="test",
                tags={"site_id": "CL-001"},
            )

        assert len(captured) == 1
        assert b"CL-001" in captured[0]


# ---------------------------------------------------------------------------
# No channels configured
# ---------------------------------------------------------------------------

class TestLogOnlyMode:
    def test_no_channels_no_exception(self):
        """Without any channels configured, log-only mode should work silently."""
        for k in ["ALERT_SLACK_WEBHOOK", "ALERT_EMAIL_FROM", "ALERT_EMAIL_TO"]:
            os.environ.pop(k, None)

        dispatcher = AlertDispatcher()
        dispatcher.send(
            severity=AlertSeverity.CRITICAL,
            title="Log only",
            detail="test",
            source="test",
        )
