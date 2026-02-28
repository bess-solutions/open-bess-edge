# SPDX-License-Identifier: Apache-2.0
"""
tests/test_compliance_api.py
Tests for the compliance REST API endpoint.
"""

from __future__ import annotations

import io
import json
from http.server import HTTPServer
from unittest.mock import patch

import pytest

# Import directly (bypasses interfaces/__init__.py which has VPP deps)
from src.interfaces.compliance_api import (
    _compliance_state,
    make_compliance_handler,
    update_compliance_state,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class _MockSocket:
    """Minimal socket-like for handler tests without a real server."""

    def __init__(self) -> None:
        self._recv_data = b""
        self.response = io.BytesIO()

    def makefile(self, mode: str, *args: object) -> io.BufferedIOBase:
        if mode == "rb":
            return io.BufferedReader(io.BytesIO(self._recv_data))  # type: ignore[arg-type]
        return io.BufferedWriter(self.response)  # type: ignore[return-value]

    def sendall(self, data: bytes) -> None:
        self.response.write(data)

    def getsockname(self) -> tuple[str, int]:
        return ("127.0.0.1", 8000)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateComplianceState:
    def test_update_sets_all_fields(self) -> None:
        update_compliance_state(
            site_id="SITE-CL-TEST",
            all_ok=True,
            violations=[],
            score=98.5,
            cycle=42,
        )
        assert _compliance_state["site_id"] == "SITE-CL-TEST"
        assert _compliance_state["all_ok"] is True
        assert _compliance_state["compliance_score"] == 98.5
        assert _compliance_state["cycle_count"] == 42
        assert _compliance_state["violations"] == []

    def test_update_with_violations(self) -> None:
        update_compliance_state(
            site_id="SITE-CL-002",
            all_ok=False,
            violations=["GAP-003: CEN mTLS not configured"],
            score=75.0,
            cycle=1,
        )
        assert _compliance_state["all_ok"] is False
        assert "GAP-003" in _compliance_state["violations"][0]
        assert _compliance_state["compliance_score"] == 75.0


class TestComplianceHandler:
    def _get_response(self, path: str, site_id: str = "SITE-CL-TEST") -> tuple[int, dict]:
        """Build handler and simulate a GET request, return (status_code, json_body)."""
        HandlerClass = make_compliance_handler(site_id, "v2.13.0-test")

        captured_code: list[int] = []
        captured_body: list[bytes] = []

        class _FakeHandler(HandlerClass):  # type: ignore[valid-type]
            def __init__(self) -> None:  # type: ignore[override]
                # Don't call super().__init__ — skip socket setup
                self.path = path
                self.headers: dict = {}  # type: ignore[assignment]
                self._sent_code: int | None = None
                self._body = io.BytesIO()

            def send_response(self, code: int, message: str | None = None) -> None:
                captured_code.append(code)

            def send_header(self, key: str, value: str) -> None:
                pass

            def end_headers(self) -> None:
                pass

            @property
            def wfile(self) -> io.BytesIO:  # type: ignore[override]
                return self._body

        h = _FakeHandler()
        h.do_GET()

        body = json.loads(h._body.getvalue()) if h._body.getvalue() else {}
        code = captured_code[0] if captured_code else 0
        return code, body

    def test_status_endpoint_compliant(self) -> None:
        update_compliance_state("SITE-CL-TEST", True, [], 100.0, 1)
        code, body = self._get_response("/compliance/status")
        assert code == 200
        assert body["status"] == "compliant"
        assert body["compliance_score"] == 100.0

    def test_status_endpoint_non_compliant(self) -> None:
        update_compliance_state("SITE-CL-TEST", False, ["GAP-003"], 80.0, 2)
        code, body = self._get_response("/compliance/status")
        assert code == 503
        assert body["status"] == "non_compliant"

    def test_report_endpoint_structure(self) -> None:
        update_compliance_state("SITE-CL-TEST", True, [], 100.0, 10)
        _, body = self._get_response("/compliance/report")
        assert body["report_type"] == "NTSyCS_COMPLIANCE_REPORT"
        assert "gaps" in body
        assert "GAP-001" in body["gaps"]
        assert "GAP-011" in body["gaps"]
        assert body["gaps_checked"] == 11

    def test_unknown_path_returns_404(self) -> None:
        code, body = self._get_response("/invalid/path")
        assert code == 404
        assert body["error"] == "Not found"
