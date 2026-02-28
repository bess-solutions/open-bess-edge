# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_cen_publisher.py
============================
Unit tests for ``src.core.publishers.cen_publisher.CENPublisher``
NTSyCS Cap. 6.1 / Anexo 8 — Telemetría CEN con mTLS (GAP-003).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from src.core.publishers.cen_publisher import CENPublisher, CENTelemetryPayload


SAMPLE_TELEMETRY = {
    "soc_pct": 72.5,
    "p_kw": 450.0,
    "q_kvar": -20.0,
    "f_hz": 49.95,
    "status": "ONLINE",
    "bess_temp_c": 28.5,
}


@pytest.fixture()
def dry_run_publisher() -> CENPublisher:
    return CENPublisher(endpoint_url=None, site_id="TEST-SITE", dry_run=True)


@pytest.fixture()
def live_publisher() -> CENPublisher:
    return CENPublisher(
        endpoint_url="https://cen.coordinador.cl/telemetry",
        site_id="TEST-SITE",
        dry_run=False,
    )


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class TestDryRunMode:
    def test_dry_run_returns_true(self, dry_run_publisher: CENPublisher) -> None:
        result = asyncio.run(dry_run_publisher.publish(SAMPLE_TELEMETRY))
        assert result is True

    def test_dry_run_no_network_call(self, dry_run_publisher: CENPublisher) -> None:
        with patch.object(dry_run_publisher, "_do_http_post") as mock_http:
            asyncio.run(dry_run_publisher.publish(SAMPLE_TELEMETRY))
        mock_http.assert_not_called()

    def test_dry_run_property(self, dry_run_publisher: CENPublisher) -> None:
        assert dry_run_publisher.dry_run is True

    def test_no_endpoint_becomes_dry_run(self) -> None:
        pub = CENPublisher(endpoint_url="")
        assert pub.dry_run is True

    def test_missing_fields_use_defaults(self, dry_run_publisher: CENPublisher) -> None:
        result = asyncio.run(dry_run_publisher.publish({}))
        assert result is True


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    def test_retries_on_error_then_succeeds(self, live_publisher: CENPublisher) -> None:
        call_count = 0

        async def flaky_post(body: bytes) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("transient")

        async def run_test() -> bool:
            with patch.object(live_publisher, "_do_http_post", side_effect=flaky_post):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    return await live_publisher.publish(SAMPLE_TELEMETRY)

        result = asyncio.run(run_test())
        assert result is True
        assert call_count == 3

    def test_all_retries_fail_returns_false(self, live_publisher: CENPublisher) -> None:
        async def always_fail(body: bytes) -> None:
            raise OSError("persistent")

        async def run_test() -> bool:
            with patch.object(live_publisher, "_do_http_post", side_effect=always_fail):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    return await live_publisher.publish(SAMPLE_TELEMETRY)

        result = asyncio.run(run_test())
        assert result is False


# ---------------------------------------------------------------------------
# Properties / from_env
# ---------------------------------------------------------------------------


class TestProperties:
    def test_interval_default(self, dry_run_publisher: CENPublisher) -> None:
        assert dry_run_publisher.interval_s == pytest.approx(60.0)

    def test_from_env_dry_run_when_no_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("CEN_ENDPOINT_URL", raising=False)
        monkeypatch.setenv("CEN_SITE_ID", "ENV-SITE")
        pub = CENPublisher.from_env()
        assert pub.dry_run is True

    def test_from_env_reads_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CEN_ENDPOINT_URL", "https://cen.test/api")
        monkeypatch.setenv("CEN_INTERVAL_S", "30")
        monkeypatch.delenv("CEN_CA_CERT", raising=False)
        pub = CENPublisher.from_env()
        assert pub.interval_s == pytest.approx(30.0)
