# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 BESS Solutions SpA

"""
tests/test_server_totp_rate_limit.py
======================================
Unit tests for TOTP setpoint authentication gate and Rate Limiter middleware.
"""

import os
from unittest.mock import patch
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from src.interfaces.server import BESSAIServer, _RATE_LIMIT_STORE


@pytest.fixture
def reset_rate_limit():
    _RATE_LIMIT_STORE.clear()
    yield
    _RATE_LIMIT_STORE.clear()


@pytest.mark.asyncio
async def test_setpoint_requires_totp_when_mfa_secret_set(reset_rate_limit):
    os.environ["DASHBOARD_MFA_SECRET"] = "JBSWY3DPEHPK3PXP"
    server = BESSAIServer(site_id="TEST-SITE")
    app = server._app

    async with TestClient(TestServer(app)) as client:
        # Request without TOTP token -> 401
        resp = await client.post("/api/v1/setpoint", json={"target_kw": 50.0})
        assert resp.status == 401
        body = await resp.json()
        assert body["error"] == "unauthorized"

        # Request with invalid TOTP token -> 401
        headers = {"X-TOTP-Token": "000000"}
        resp_invalid = await client.post("/api/v1/setpoint", json={"target_kw": 50.0}, headers=headers)
        assert resp_invalid.status == 401

    os.environ.pop("DASHBOARD_MFA_SECRET", None)


@pytest.mark.asyncio
async def test_rate_limiter_allows_normal_traffic(reset_rate_limit):
    server = BESSAIServer(site_id="TEST-SITE")
    app = server._app

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
